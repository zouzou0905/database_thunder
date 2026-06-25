from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable


RANK_RANGE_RE = re.compile(r"_(\d+)_(\d+)\.csv$", re.IGNORECASE)
MAX_REASONABLE_RANK_RANGE = 1_000_000

FIELD_MAP = {
    "serial_no": "序号",
    "keyword": "关键词",
    "translation": "关键词释义",
    "search_volume": "月搜索量",
    "current_rank": "现排名",
    "history_rank": "历史排名",
    "rank_change": "排名变化",
    "rank_change_rate": "排名变化率",
    "impressions_clicks": "展示量/点击量",
    "ppc_bid": "PPC竞价",
    "spr": "SPR",
    "category": "所属类目",
    "click_share": "点击总占比",
    "conversion_share": "转化总占比",
    "page_no": "页码",
}


def load_env_file(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_database_url() -> str:
    load_env_file()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and update it.")
    return url


def parse_month(value: str) -> date:
    parts = value.split("-")
    if len(parts) != 2:
        raise ValueError(f"Month must use YYYY-MM format: {value}")
    return date(int(parts[0]), int(parts[1]), 1)


def add_months(month: date, offset: int) -> date:
    year = month.year + (month.month - 1 + offset) // 12
    new_month = (month.month - 1 + offset) % 12 + 1
    return date(year, new_month, 1)


def iter_csv_files(inputs: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for item in inputs:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(path.glob("*.csv")))
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(item)
    return files


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_rank_range(file_name: str) -> tuple[int | None, int | None]:
    groups = [int(value) for value in re.findall(r"\d+", Path(file_name).stem)]
    candidates: list[tuple[int, int]] = []
    for left, right in zip(groups, groups[1:]):
        if 0 <= left <= right <= MAX_REASONABLE_RANK_RANGE:
            candidates.append((left, right))
    if candidates:
        return candidates[-1]

    match = RANK_RANGE_RE.search(file_name)
    if not match:
        return None, None
    left, right = int(match.group(1)), int(match.group(2))
    if right > MAX_REASONABLE_RANK_RANGE:
        return None, None
    return left, right


def normalize_keyword(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\ufeff", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().lower()


def keyword_hash(normalized_keyword: str) -> str:
    return hashlib.sha1(normalized_keyword.encode("utf-8")).hexdigest()


def parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "N/A", "n/a"}:
        return None
    text = text.replace(",", "")
    text = re.sub(r"^[^\d\-.]+", "", text)
    text = text.replace("%", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_int(value: str | None) -> int | None:
    number = parse_decimal(value)
    if number is None:
        return None
    return int(number)


def parse_percent(value: str | None) -> Decimal | None:
    number = parse_decimal(value)
    if number is None:
        return None
    return number / Decimal("100")


def split_pipe(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).split("|")]


def parse_history_ranks(value: str | None) -> tuple[int | None, int | None, int | None]:
    parts = split_pipe(value)
    values = parts[-3:] if len(parts) >= 3 else parts
    while len(values) < 3:
        values.append("")
    return tuple(parse_int(item) for item in values[:3])


def parse_history_numbers(value: str | None) -> tuple[int | None, int | None, int | None]:
    parts = split_pipe(value)
    while len(parts) < 3:
        parts.append("")
    return tuple(parse_int(item) for item in parts[:3])


def parse_history_percents(value: str | None) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    parts = split_pipe(value)
    while len(parts) < 3:
        parts.append("")
    return tuple(parse_percent(item) for item in parts[:3])


def parse_two_numbers(value: str | None) -> tuple[Decimal | None, Decimal | None]:
    parts = split_pipe(value)
    while len(parts) < 2:
        parts.append("")
    return parse_decimal(parts[0]), parse_decimal(parts[1])


def parse_three_money_values(value: str | None) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    parts = split_pipe(value)
    while len(parts) < 3:
        parts.append("")
    return tuple(parse_decimal(item) for item in parts[:3])


def word_count(keyword: str) -> int:
    return len([part for part in keyword.split(" ") if part])
