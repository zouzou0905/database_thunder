# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Amazon ABA / SellerSprite keyword trend database and operations workspace. CSV keyword data is imported, normalized, scored, and surfaced through a React operations UI for keyword opportunity discovery. The system focuses only on keyword-dimension data — it does not depend on product pricing, profit, or full ASIN/competitor dimensions.

## Commands

### Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1    # activate (PowerShell)
```

### Database

```powershell
python scripts/init_db.py       # initialize schema, indexes, and views
```

### Data Pipeline (must be run in order)

```powershell
python scripts/inspect_csv.py --input "path/to/csv/folder" --output data/reports/YYYY-MM-inspect.json
python scripts/import_csv.py --month YYYY-MM --marketplace UK --input "path/to/csv/folder"
python scripts/calculate_trends.py --analysis-month YYYY-MM --marketplace UK
```

`calculate_trends.py` accepts `--all` to recalculate all imported months chronologically, with optional `--from-month`, `--to-month`, and `--year` filters. Use `--skip-cache-refresh` only when intentionally avoiding cache-table writes.

### Cache Refresh (when the UI shows "实时计算" / slow-query warning)

```powershell
python scripts/refresh_product_selection_cache.py --analysis-month YYYY-MM --marketplace UK
```

### Backend (FastAPI, port 8001)

```powershell
python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8001 --reload
```

API docs at `http://127.0.0.1:8001/docs`, health at `/api/health`.

### Frontend (React + Vite, port 8000)

```powershell
cd frontend
npm run dev     # starts Vite dev server on 0.0.0.0:8000
npm run build   # production build
```

### Tests

```powershell
python -m unittest discover -s tests     # run all tests
python -m py_compile scripts/common.py scripts/init_db.py scripts/import_csv.py scripts/calculate_trends.py scripts/inspect_csv.py   # syntax check
```

## Architecture

### Four-Layer Data Model

1. **Import management** — `import_batches`, `source_files` (file-hash deduplication prevents re-import)
2. **Raw & normalized** — `raw_aba_rows` (original CSV rows as JSON), `keywords` (normalized + SHA1-hashed), `keyword_monthly_metrics` (core fact table for all downstream analysis)
3. **Analysis & calculation** — `keyword_monthly_trends` (MoM/YoY trends), `keyword_ops_monthly` (operational wide table with scores), `keyword_selection_candidates_monthly` (opportunity pool cache), `keyword_compare_snapshot_monthly` (cross-month comparison cache)
4. **Operations actions** — `users`, `keyword_user_actions` (favorites, status, notes), `keyword_selection_exclusions` (brand/irrelevant/risk term rules)

### Pre-computation Strategy

All user-facing pages query **cache tables** first (`keyword_selection_candidates_monthly`, `keyword_compare_snapshot_monthly`). The real-time view `v_mb_product_selection_candidates` exists only as a fallback. The API returns `cached: false` when falling back, and the frontend shows a slow-query warning. Cache is never rebuilt on API startup — it must be triggered deliberately via `calculate_trends.py` or the scheduler's `cache_refresh_loop()`.

### Backend Structure (`backend/app/`)

- `main.py` — FastAPI app factory, CORS, router registration
- `pool.py` — Singleton psycopg `ConnectionPool` (min=2, max=30, 1h lifetime)
- `db.py` — `get_connection()` context manager; sets `statement_timeout = 30s` per connection
- `core/config.py` — `Settings` dataclass loaded from `.env`; `.env` parsing without python-dotenv dependency
- `core/security.py` — Custom HMAC-SHA256 token auth (not JWT, but JWT-like payload structure); PBKDF2-SHA256 password hashing
- `core/cache.py` — In-memory dict cache with TTL, namespace-based invalidation; `@cached()` decorator with `exclude` for conn arguments
- `api/` — Route modules: `auth`, `product_selection`, `keyword_compare`, `exclusions`, `exports`, `meta`, `health`, `users`
- `services/` — Business logic: `product_selection.py`, `product_selection_cache.py`, `keyword_compare.py`, `keyword_compare_snapshot.py`, `exclusions.py`, `users.py`, `scheduler.py`
- `utils/json.py` — Decimal-aware JSON serialization

### Frontend Structure (`frontend/src/`)

Single-page React app with no routing library — the side nav toggles between four views managed by `activeView` state:
- **Opportunities pool** — Filterable keyword table with 9 scope presets (all, candidate, priority, rising, stable, new, low-competition, high-demand, review). Each scope applies specific filter defaults.
- **Favorites** — Same table filtered to `favorite_only: true`
- **Cross-month compare** — Per-keyword multi-month comparison with trend classification (continuous, rising, falling, volatile, etc.)
- **Exclusion rules** — CRUD for brand/irrelevant/risk/competitor term rules

Key patterns:
- `api.ts` — All API calls; includes client-side request caching (Map with TTL, 5min for candidates, 2min for compare)
- `types.ts` — All TypeScript interfaces
- UI uses hand-built `AppleSelect` component; Lucide React icons; no component library

### CSV Parsing (`scripts/common.py`)

- Keywords normalized: NFKC → BOM removal → whitespace collapse → strip → lowercase
- `keyword_hash()` uses SHA1 of the normalized keyword (conflict resolution on the `keywords` table)
- `file_sha256()` hashes entire CSV files to detect duplicates
- `parse_rank_range()` extracts rank ranges from SellerSprite file naming conventions
- Pipe-delimited fields (e.g. history ranks, PPC bids) are split and parsed as tuples

### Month Convention

"Analysis month" is an operational concept, not the current calendar month. The user selects `YYYY-MM` in the UI; the backend converts to `YYYY-MM-01`. Cross-month ranges use the same convention. A month must be imported before it appears in the API.

### Important Constraints

- Do NOT let the frontend connect directly to PostgreSQL — all data access goes through FastAPI
- Do NOT rebuild caches on API startup — cache refresh is a separate, deliberate operation
- SQL schema changes must be in `sql/` directory files, not ad-hoc pgAdmin modifications
- Do NOT mix backend frameworks (no Express) or frontend frameworks (no Vue)
- The `docs/archive/` directory contains historical design notes; current authoritative docs are at `docs/` root
