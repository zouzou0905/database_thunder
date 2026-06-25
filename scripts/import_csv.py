from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg

from common import (
    FIELD_MAP,
    file_sha256,
    get_database_url,
    iter_csv_files,
    keyword_hash,
    normalize_keyword,
    parse_history_numbers,
    parse_history_percents,
    parse_history_ranks,
    parse_int,
    parse_month,
    parse_percent,
    parse_rank_range,
    parse_three_money_values,
    parse_two_numbers,
    word_count,
)


def print_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def create_batch(conn: psycopg.Connection, batch_name: str, data_month, marketplace: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO import_batches (batch_name, data_month, marketplace)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (batch_name, data_month, marketplace),
        )
        return cur.fetchone()[0]


def upsert_source_file(
    conn: psycopg.Connection,
    batch_id: int,
    path: Path,
    file_hash: str,
    data_month,
    marketplace: str,
    row_count: int,
) -> tuple[int, bool]:
    rank_start, rank_end = parse_rank_range(path.name)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_files (
                batch_id, file_name, file_path, file_hash, marketplace,
                data_month, rank_start, rank_end, row_count
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (file_hash) DO NOTHING
            RETURNING id
            """,
            (
                batch_id,
                path.name,
                str(path),
                file_hash,
                marketplace,
                data_month,
                rank_start,
                rank_end,
                row_count,
            ),
        )
        row = cur.fetchone()
        if row:
            return row[0], False
        cur.execute("SELECT id FROM source_files WHERE file_hash = %s", (file_hash,))
        return cur.fetchone()[0], True


def insert_raw_row(
    cur: psycopg.Cursor,
    source_file_id: int,
    row_number: int,
    data_month,
    marketplace: str,
    row: dict[str, Any],
) -> int:
    cur.execute(
        """
        INSERT INTO raw_aba_rows (
            source_file_id, row_number, data_month, marketplace, raw_keyword,
            raw_rank, raw_search_volume, raw_click_share, raw_conversion_share,
            raw_top_asins, raw_payload
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_file_id, row_number) DO UPDATE SET
            raw_payload = EXCLUDED.raw_payload
        RETURNING id
        """,
        (
            source_file_id,
            row_number,
            data_month,
            marketplace,
            row.get(FIELD_MAP["keyword"]),
            row.get(FIELD_MAP["current_rank"]),
            row.get(FIELD_MAP["search_volume"]),
            row.get(FIELD_MAP["click_share"]),
            row.get(FIELD_MAP["conversion_share"]),
            None,
            json.dumps(row, ensure_ascii=False),
        ),
    )
    return cur.fetchone()[0]


def upsert_keyword(cur: psycopg.Cursor, raw_keyword: str) -> int | None:
    normalized = normalize_keyword(raw_keyword)
    if not normalized:
        return None
    digest = keyword_hash(normalized)
    cur.execute(
        """
        INSERT INTO keywords (
            keyword_raw, keyword_normalized, keyword_hash, word_count, char_count
        )
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (keyword_hash) DO UPDATE SET
            keyword_raw = EXCLUDED.keyword_raw,
            updated_at = NOW()
        RETURNING id
        """,
        (raw_keyword, normalized, digest, word_count(normalized), len(normalized)),
    )
    return cur.fetchone()[0]


def upsert_metric(
    cur: psycopg.Cursor,
    keyword_id: int,
    data_month,
    marketplace: str,
    source_file_id: int,
    raw_row_id: int,
    row: dict[str, Any],
) -> None:
    prev_rank, four_rank, twelve_rank = parse_history_ranks(row.get(FIELD_MAP["history_rank"]))
    prev_change, four_change, twelve_change = parse_history_numbers(row.get(FIELD_MAP["rank_change"]))
    prev_rate, four_rate, twelve_rate = parse_history_percents(row.get(FIELD_MAP["rank_change_rate"]))
    impressions, clicks = parse_two_numbers(row.get(FIELD_MAP["impressions_clicks"]))
    ppc_low, ppc_mid, ppc_high = parse_three_money_values(row.get(FIELD_MAP["ppc_bid"]))

    cur.execute(
        """
        INSERT INTO keyword_monthly_metrics (
            keyword_id, data_month, marketplace, serial_no, keyword_translation,
            category, page_no, search_rank, search_volume, prev_month_rank,
            four_months_ago_rank, twelve_months_ago_rank, rank_change_prev_month,
            rank_change_four_months, rank_change_twelve_months,
            rank_change_rate_prev_month, rank_change_rate_four_months,
            rank_change_rate_twelve_months, impressions, clicks, ppc_bid_low,
            ppc_bid_mid, ppc_bid_high, spr, click_share, conversion_share,
            source_file_id, raw_row_id
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (keyword_id, data_month, marketplace) DO UPDATE SET
            serial_no = EXCLUDED.serial_no,
            keyword_translation = EXCLUDED.keyword_translation,
            category = EXCLUDED.category,
            page_no = EXCLUDED.page_no,
            search_rank = EXCLUDED.search_rank,
            search_volume = EXCLUDED.search_volume,
            prev_month_rank = EXCLUDED.prev_month_rank,
            four_months_ago_rank = EXCLUDED.four_months_ago_rank,
            twelve_months_ago_rank = EXCLUDED.twelve_months_ago_rank,
            rank_change_prev_month = EXCLUDED.rank_change_prev_month,
            rank_change_four_months = EXCLUDED.rank_change_four_months,
            rank_change_twelve_months = EXCLUDED.rank_change_twelve_months,
            rank_change_rate_prev_month = EXCLUDED.rank_change_rate_prev_month,
            rank_change_rate_four_months = EXCLUDED.rank_change_rate_four_months,
            rank_change_rate_twelve_months = EXCLUDED.rank_change_rate_twelve_months,
            impressions = EXCLUDED.impressions,
            clicks = EXCLUDED.clicks,
            ppc_bid_low = EXCLUDED.ppc_bid_low,
            ppc_bid_mid = EXCLUDED.ppc_bid_mid,
            ppc_bid_high = EXCLUDED.ppc_bid_high,
            spr = EXCLUDED.spr,
            click_share = EXCLUDED.click_share,
            conversion_share = EXCLUDED.conversion_share,
            source_file_id = EXCLUDED.source_file_id,
            raw_row_id = EXCLUDED.raw_row_id,
            updated_at = NOW()
        """,
        (
            keyword_id,
            data_month,
            marketplace,
            parse_int(row.get(FIELD_MAP["serial_no"])),
            row.get(FIELD_MAP["translation"]),
            row.get(FIELD_MAP["category"]),
            parse_int(row.get(FIELD_MAP["page_no"])),
            parse_int(row.get(FIELD_MAP["current_rank"])),
            parse_int(row.get(FIELD_MAP["search_volume"])),
            prev_rank,
            four_rank,
            twelve_rank,
            prev_change,
            four_change,
            twelve_change,
            prev_rate,
            four_rate,
            twelve_rate,
            impressions,
            clicks,
            ppc_low,
            ppc_mid,
            ppc_high,
            parse_int(row.get(FIELD_MAP["spr"])),
            parse_percent(row.get(FIELD_MAP["click_share"])),
            parse_percent(row.get(FIELD_MAP["conversion_share"])),
            source_file_id,
            raw_row_id,
        ),
    )


def import_file(conn: psycopg.Connection, batch_id: int, path: Path, data_month, marketplace: str, force: bool) -> dict[str, int]:
    rows = read_csv_rows(path)
    digest = file_sha256(path)
    source_file_id, already_imported = upsert_source_file(
        conn, batch_id, path, digest, data_month, marketplace, len(rows)
    )
    if already_imported and not force:
        return {"files": 1, "rows": len(rows), "valid": 0, "duplicates": len(rows), "errors": 0}

    valid = 0
    errors = 0
    with conn.cursor() as cur:
        for index, row in enumerate(rows, start=1):
            try:
                raw_keyword = row.get(FIELD_MAP["keyword"], "")
                keyword_id = upsert_keyword(cur, raw_keyword)
                raw_row_id = insert_raw_row(cur, source_file_id, index, data_month, marketplace, row)
                if keyword_id is None:
                    errors += 1
                    continue
                upsert_metric(cur, keyword_id, data_month, marketplace, source_file_id, raw_row_id, row)
                valid += 1
            except Exception:
                errors += 1
    return {"files": 1, "rows": len(rows), "valid": valid, "duplicates": 0, "errors": errors}


def update_batch(conn: psycopg.Connection, batch_id: int, stats: dict[str, int], status: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE import_batches
            SET finished_at = %s,
                status = %s,
                total_files = %s,
                total_rows = %s,
                valid_rows = %s,
                duplicate_rows = %s,
                error_rows = %s
            WHERE id = %s
            """,
            (
                datetime.now(),
                status,
                stats["files"],
                stats["rows"],
                stats["valid"],
                stats["duplicates"],
                stats["errors"],
                batch_id,
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import SellerSprite ABA CSV files.")
    parser.add_argument("--month", required=True, help="Analysis data month, format YYYY-MM.")
    parser.add_argument("--marketplace", default="US", help="Marketplace code, default US.")
    parser.add_argument("--input", required=True, nargs="+", help="CSV file or directory.")
    parser.add_argument("--batch-name", help="Optional import batch name.")
    parser.add_argument("--force", action="store_true", help="Reprocess files already recorded by file hash.")
    parser.add_argument("--progress-every", type=int, default=10, help="Print progress every N files, default 10.")
    args = parser.parse_args()

    data_month = parse_month(args.month)
    files = iter_csv_files(args.input)
    if not files:
        raise RuntimeError("No CSV files found.")
    total_files = len(files)
    progress_every = max(args.progress_every, 1)

    stats = {"files": 0, "rows": 0, "valid": 0, "duplicates": 0, "errors": 0}
    batch_name = args.batch_name or f"import-{args.month}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    with psycopg.connect(get_database_url()) as conn:
        batch_id = create_batch(conn, batch_name, data_month, args.marketplace)
        started_at = datetime.now()
        print_progress(
            f"[import] start batch={batch_name} month={args.month} marketplace={args.marketplace} files={total_files}"
        )
        try:
            for index, path in enumerate(files, start=1):
                file_stats = import_file(conn, batch_id, path, data_month, args.marketplace, args.force)
                for key in stats:
                    stats[key] += file_stats[key]
                conn.commit()
                if index % progress_every == 0 or index == total_files:
                    elapsed = datetime.now() - started_at
                    print_progress(
                        "[import] "
                        f"{index}/{total_files} files "
                        f"rows={stats['rows']} valid={stats['valid']} "
                        f"duplicates={stats['duplicates']} errors={stats['errors']} "
                        f"elapsed={str(elapsed).split('.')[0]} "
                        f"last={path.name}"
                    )
            update_batch(conn, batch_id, stats, "finished")
            conn.commit()
            print_progress(f"[import] finished batch={batch_name}")
        except Exception:
            conn.rollback()
            update_batch(conn, batch_id, stats, "failed")
            conn.commit()
            print_progress(f"[import] failed batch={batch_name}")
            raise

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
