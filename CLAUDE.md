# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Amazon ABA / SellerSprite keyword trend database and operations workspace. CSV keyword data is imported, normalized, scored, and surfaced through a React operations UI for keyword opportunity discovery. Focused on keyword-dimension data only — no product pricing, profit, or ASIN dimensions.

**Current deployment:** Windows 11 Pro, PostgreSQL 17, D:\database\database_thunder-main, LAN IP 192.168.0.135.

## Commands

Always run from project root. All Python commands need `PYTHONPATH=backend` for `app.*` imports.

### Backend (FastAPI, port 8001)

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8001
```

### Frontend (React + Vite, port 8000)

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://192.168.0.135:8001/api"
npm run dev     # --host 0.0.0.0 --port 8000
```

### Database Init

```powershell
python scripts/init_db.py
```

Note: `init_db.py` does NOT include `sql/schema/004_keyword_compare_snapshot.sql` or `005_keyword_compare_snapshot_stats.sql`. These must be run manually if the table is missing.

### Data Pipeline (run in order)

```powershell
python scripts/inspect_csv.py --input "D:\PostgreSQL\data\aba数据\YYYY-MM" --output data/reports/YYYY-MM-inspect.json
python scripts/import_csv.py --month YYYY-MM --marketplace UK --input "D:\PostgreSQL\data\aba数据\YYYY-MM"
python scripts/calculate_trends.py --analysis-month YYYY-MM --marketplace UK
```

Recalculate all months:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe scripts/calculate_trends.py --all --marketplace UK
```

After importing a new month, ALWAYS run `calculate_trends.py` to populate trends, ops, cache, and snapshot tables.

### User Management

```powershell
python scripts/create_app_user.py --account admin --display-name "管理员" --role admin --password <password>
```

### Tests

```powershell
python -m unittest discover -s tests
cd frontend && npx tsc --noEmit    # TypeScript check
```

## Current Data State

- **Data months:** 2025-04 through 2026-04 (13 months), all marketplace=UK
- **Database size:** 20 GB (on D: drive, 3.7 TB total, 3.6 TB free)
- **Keywords:** ~300K unique per month across keyword_monthly_metrics
- **Compare snapshot:** 1,023,738 keywords in keyword_compare_snapshot
- **User:** admin / 123456 (role=admin)
- **.env DATABASE_URL:** `postgresql://keyword_user:keyword_user_123456@localhost:5432/keyword_trends`
- **DEFAULT_MARKETPLACE:** UK

## Architecture

### Four-Layer Data Model

1. **Import management** — `import_batches`, `source_files` (SHA256 file-hash deduplication)
2. **Raw & normalized** — `raw_aba_rows`, `keywords` (SHA1-hashed normalized keyword), `keyword_monthly_metrics` (core fact table)
3. **Analysis & calculation** — `keyword_monthly_trends`, `keyword_ops_monthly`, `keyword_selection_candidates_monthly` (cache), `keyword_compare_snapshot` (NOT `_monthly` suffix)
4. **Operations actions** — `app_users`, `keyword_selection_states` (favorites/status), `keyword_selection_notes`, `keyword_selection_exclusions`

### Pre-computation Strategy

All pages query cache tables. The real-time view `v_mb_product_selection_candidates` is fallback only. API returns `cached: false` when falling back. Cache is never rebuilt on startup — run `calculate_trends.py` deliberately.

### Compare Snapshot Classification (5-category)

`keyword_compare_snapshot` uses statistical columns (avg, stddev, CV, regression slope, R², gap_count) computed in Step 6.5 of `refresh_compare_snapshot()`, classified in Step 7:

| Type | Condition |
|------|-----------|
| rising (上升型) | ≥4 data points, positive slope, slope/avg > 0.05, R² ≥ 0.25 |
| falling (下降型) | ≥4 data points, negative slope, abs(slope)/avg > 0.05, R² ≥ 0.25 |
| stable (常年稳定型) | ≥5 months, avg ≥ 100, CV < 0.25, no strong trend |
| seasonal (季节型) | gap_count 1-4, ≥3 months, avg ≥ 100 |
| volatile (波动型) | everything else |

**Known classification issue:** `stable` doesn't check `gap_count`, so keywords appearing in only 5 flat months out of 13 can be misclassified as stable.

### Backend (`backend/app/`)

- `main.py` — FastAPI app factory
- `pool.py` — psycopg ConnectionPool (min=2, max=30, 1h lifetime)
- `db.py` — `get_connection()` sets `statement_timeout=30s` and `lock_timeout=5s` per connection
- `core/config.py` — Settings from `.env`
- `core/security.py` — HMAC-SHA256 token auth, PBKDF2-SHA256 password hashing
- `core/cache.py` — In-memory dict cache with TTL, `@cached()` decorator
- `api/exports.py` — Export module supporting candidates/compare sources, Excel/CSV, custom filename, accurate COUNT preview
- `services/keyword_compare_snapshot.py` — Multi-step snapshot refresh (temp table → stats → 5-category classification)
- `services/scheduler.py` — Background cache refresh loop (NOT auto-started)

### Frontend (`frontend/src/`)

Single-page React app, no routing library. Side nav toggles 5 views via `activeView` state:

- **机会池** — 9 scope presets with specific filter defaults
- **我的收藏** — Same table filtered to favorites
- **横向对比** — Per-keyword multi-month comparison with sparkline trend chart, PPC/SPR columns, page size selector (10/50/100)
- **禁用词** — CRUD for exclusion rules
- **数据导出** — Independent export module with source selector, filters, count preview, custom filename, Excel/CSV format

Key components:
- `AppleSelect` — Hand-built dropdown with `compact` and `dropUp` props
- `Sparkline` — SVG trend chart with portal-rendered tooltip (per-data-point hover, auto flips below when near viewport top)
- Page size selector in both opportunities and compare pagination bars

### CSV Parsing (`scripts/common.py`)

- Keywords: NFKC → BOM removal → whitespace collapse → strip → lowercase
- `keyword_hash()` = SHA1 of normalized keyword
- `file_sha256()` = SHA256 of whole CSV for deduplication
- Pipe-delimited fields parsed as tuples (PPC: low/mid/high)

## PostgreSQL Performance Configuration

PostgreSQL 17 config at `D:\PostgreSQL\17\data\postgresql.conf` (backup at `.backup`):

| Parameter | Value | Note |
|-----------|-------|------|
| `shared_buffers` | 512MB | Windows limit without Lock Pages privilege |
| `effective_cache_size` | 24GB | OS-level cache hint |
| `work_mem` | 64MB | |
| `maintenance_work_mem` | 512MB | |
| `random_page_cost` | 1.1 | SSD (was 4.0 HDD) |
| `effective_io_concurrency` | 0 | Windows doesn't support posix_fadvise |
| `max_parallel_workers_per_gather` | 4 | |
| `wal_buffers` | 64MB | |
| `jit` | off | Short API queries don't benefit |

Windows service: `postgresql-x64-17` (requires admin to restart).

## Git

- **Remote:** `https://github.com/zouzou0905/database_thunder.git` (origin/main)
- **Local:** `main` tracking `origin/main`
- **User:** kai / 2132763052@qq.com
- First pull after init needs `--allow-unrelated-histories`. Subsequent: `git pull` works normally.

## Important Constraints

- `calculate_trends.py` requires `PYTHONPATH=backend` for `from app.services...` imports
- `init_db.py` does NOT auto-create `keyword_compare_snapshot` — run 004/005 SQL manually if missing
- Never let frontend connect directly to PostgreSQL
- Never rebuild caches on API startup
- SQL schema changes go in `sql/` directory files
- Do not mix backend/frontend frameworks
- Authoritative docs: `docs/` root. Historical: `docs/archive/`
- Windows admin required for: PostgreSQL service restart, firewall rules, `effective_io_concurrency` changes
