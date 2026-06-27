from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from common import FIELD_MAP, iter_csv_files, normalize_keyword, parse_int


def inspect_file(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        missing_headers = [name for name in FIELD_MAP.values() if name not in headers]
        rows = list(reader)

    keywords = [normalize_keyword(row.get(FIELD_MAP["keyword"], "")) for row in rows]
    non_empty_keywords = [keyword for keyword in keywords if keyword]
    keyword_counts = Counter(non_empty_keywords)
    duplicate_keywords = sum(count - 1 for count in keyword_counts.values() if count > 1)

    ranks = [parse_int(row.get(FIELD_MAP["current_rank"])) for row in rows]
    ranks = [rank for rank in ranks if rank is not None]
    pages = [parse_int(row.get(FIELD_MAP["page_no"])) for row in rows]
    pages = [page for page in pages if page is not None]

    return {
        "file": str(path),
        "rows": len(rows),
        "headers": headers,
        "missing_headers": missing_headers,
        "empty_keywords": len(rows) - len(non_empty_keywords),
        "duplicate_keywords": duplicate_keywords,
        "rank_min": min(ranks) if ranks else None,
        "rank_max": max(ranks) if ranks else None,
        "page_min": min(pages) if pages else None,
        "page_max": max(pages) if pages else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect SellerSprite ABA CSV files before import.")
    parser.add_argument("--input", required=True, nargs="+", help="CSV file or directory.")
    parser.add_argument("--output", help="Optional JSON report path.")
    args = parser.parse_args()

    files = iter_csv_files(args.input)
    reports = [inspect_file(path) for path in files]
    summary = {
        "files": len(reports),
        "rows": sum(item["rows"] for item in reports),
        "empty_keywords": sum(item["empty_keywords"] for item in reports),
        "duplicate_keywords_within_files": sum(item["duplicate_keywords"] for item in reports),
        "reports": reports,
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text, encoding="utf-8-sig")
    print(text)


if __name__ == "__main__":
    main()
