# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Amazon ABA / SellerSprite keyword trend database and operations workspace. CSV keyword data is imported, normalized, scored, and surfaced through a React operations UI for keyword opportunity discovery. Focused on keyword-dimension data only — no product pricing, profit, or ASIN dimensions.

**Current deployment:** Windows 11 Pro, PostgreSQL 17, D:\database\database_thunder-main, LAN IP 192.168.0.135.

## Commands

Always run from project root. All Python commands need `PYTHONPATH=backend` for `app.*` imports; admin commands need `PYTHONPATH=backend;admin`.

### Backend (FastAPI, port 8001)

```powershell
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8001
```

Note: `--app-dir backend` changes CWD to `backend/`, so `load_env_file(".env")` looks for `backend/.env`. A copy of `.env` must exist at `backend/.env` (already done — keep them in sync).

### Frontend (React + Vite, port 8000)

```powershell
cd frontend
$env:VITE_API_BASE_URL = "http://192.168.0.135:8001/api"
npm run dev     # --host 0.0.0.0 --port 8000
```

### Admin System (FastAPI + Jinja2 SSR, port 8002)

```powershell
.\admin\start_admin.ps1
# OR:
$env:PYTHONPATH = "backend;admin"
.\.venv\Scripts\python.exe -m uvicorn admin.app.main:app --host 0.0.0.0 --port 8002
```

Access: `http://192.168.0.135:8002/admin`. Login requires `role=admin`. Provides user CRUD and error log viewer. Uses Jinja2 SSR, Starlette SessionMiddleware (signed cookie, 12h TTL), and its own psycopg ConnectionPool (min=2, max=10). Full docs: `docs/09-管理系统实施方案.md`.

**Critical note:** `PYTHONPATH` MUST be `backend;admin` (backend first!) to avoid `app` package collision. The admin `start_admin.ps1` script handles this correctly.

### Database Init

```powershell
python scripts/init_db.py
```

Now includes schema files 001-011, all 4 index files, and all 3 view files. The `keyword_compare_range_cache` table (006) is UNLOGGED — data is lost on PostgreSQL restart and must be re-warmed via `calculate_trends.py`.

### Data Pipeline (run in order)

```powershell
python scripts/inspect_csv.py --input "D:\PostgreSQL\data\aba数据\YYYY-MM" --output data/reports/YYYY-MM-inspect.json
python scripts/import_csv.py --month YYYY-MM --marketplace UK --input "D:\PostgreSQL\data\aba数据\YYYY-MM"
```

After import, ALWAYS run:

```powershell
$env:PYTHONPATH = "backend"
.\.venv\Scripts\python.exe scripts/calculate_trends.py --all --marketplace UK
```

This runs 4 steps: (1) trends + ops, (2) product-selection cache, (3) full-cycle compare snapshot, (4) pre-warm 15 common range caches. Full docs: `docs/08-数据导入完整流程.md`.

### User Management

```powershell
python scripts/create_app_user.py --account admin --display-name "管理员" --role admin --password <password>
```

### Tests

```powershell
python -m unittest discover -s tests
cd frontend && npx tsc --noEmit    # TypeScript check
frontend\npx vite build            # Production build check
```

## Current Data State

- **Data months:** 2025-04 through 2026-04 (13 months), all marketplace=UK
- **Database size:** 20 GB
- **Keywords:** ~300K unique per month
- **Compare snapshot:** 1,023,738 keywords
- **Compare range cache:** ~5.5M rows across 15 intervals (UNLOGGED, lost on PG restart)
- **Holiday tags:** 44,084 rows (8,172 confirmed / 35,912 suspected) for UK, 2025 only
- **User:** admin / 123456 (role=admin)
- **.env DATABASE_URL:** `postgresql://keyword_user:keyword_user_123456@localhost:5432/keyword_trends`
- **DEFAULT_MARKETPLACE:** UK
- **.env ADMIN_SESSION_SECRET:** `admin_thunder_session_2026`
- **.env copy at backend/.env** — required because `--app-dir backend` changes CWD

## Architecture

### Four-Layer Data Model

1. **Import management** — `import_batches`, `source_files` (SHA256 file-hash deduplication)
2. **Raw & normalized** — `raw_aba_rows`, `keywords` (SHA1-hashed normalized keyword), `keyword_monthly_metrics` (core fact table)
3. **Analysis & calculation** — `keyword_monthly_trends`, `keyword_ops_monthly`, `keyword_selection_candidates_monthly` (cache), `keyword_compare_snapshot` (full-cycle snapshot), `keyword_compare_range_cache` (per-range cache, UNLOGGED), `keyword_holiday_tags` (holiday tag cache)
4. **Operations actions** — `app_users`, `keyword_selection_states` (favorites/status), `keyword_selection_notes`, `keyword_selection_exclusions`, `shared_clipboard_items`, `error_logs`, `login_history`
5. **Holiday lexicon** — `holiday_events` (festival definitions), `holiday_terms` (term dictionary), pre-seeded with Halloween (8-10月) and Christmas (10-12月) for UK

### Pre-computation Strategy

All pages query cache tables. The real-time view `v_mb_product_selection_candidates` is fallback only. API returns `cached: false` when falling back. Cache is never rebuilt on startup — run `calculate_trends.py` deliberately.

### Horizontal Compare: Three-Tier Data Source

`keyword_compare.py` recalculates per selected date range:

| Tier | Condition | Source | Speed |
|------|-----------|--------|-------|
| Full range | Full data range + snapshot exists | `keyword_compare_snapshot` | Instant |
| Cached range | Range exists in `keyword_compare_range_cache` | Cache table | ~0.5s |
| Live (cold) | New range, first query | Live CTE on `keyword_monthly_metrics` | 30-120s (auto-caches) |

`calculate_trends.py` pre-warms 15 ranges. After PG restart, re-run `calculate_trends.py --all` to rebuild UNLOGGED cache + refresh snapshot.

### Compare CTE Chain

Live CTE: `span → base → rolled → calc → calc_base → calc_full → classified`

Key computed columns in the chain:
- **rolled**: `avg_search_volume`, `prev_month_search_volume` (for 环比)
- **calc_base**: `yoy_search_volume` (JSONB extraction from monthly)
- **calc_full**: `mom_change/mom_rate`, `yoy_change/yoy_rate`
- **classified**: 5-category trend_type

### Compare Snapshot Classification (5-category)

| Type | Condition |
|------|-----------|
| rising (上升型) | ≥4 data points, positive slope, slope/avg > 0.05, R² ≥ 0.25 |
| falling (下降型) | ≥4 data points, negative slope, abs(slope)/avg > 0.05, R² ≥ 0.25 |
| stable (常年稳定型) | ≥5 months, avg ≥ 100, CV < 0.25, no strong trend |
| seasonal (季节型) | gap_count 1-4, ≥3 months, avg ≥ 100 |
| volatile (波动型) | everything else |

### Holiday Tags System

Three components:
- **Holiday lexicon**: `holiday_events` + `holiday_terms` tables. Client manages events/terms via `HolidayLexiconView`. API at `/api/holiday-lexicon`.
- **Tag computation**: `backend/app/services/holiday_tags.py` — `refresh_holiday_tags(conn, marketplace)`. Matches keyword + keyword_translation against active terms (phrase: contains, word: `\b` boundary). Confirms trend if window has ≥2 months of data, end_vol > start_vol, growth ≥ min_growth_rate, and no mid-peak collapse. Writes to `keyword_holiday_tags` cache table. API: `POST /api/holiday-tags/refresh`.
- **UI display**: Compare table has "节日标签" column (default visible). Tags are filtered to current compare range via `make_date()` in SQL. Export includes 5 holiday columns.

**Important**: Holiday tags MUST be recalculated after lexicon changes. The UI shows a stale-cache warning when terms/events are modified. Run `POST /api/holiday-tags/refresh?marketplace=UK` to rebuild. Currently 44,084 tags for UK.

### Backend (`backend/app/`)

- `main.py` — FastAPI app factory, middleware stack: CORS → ErrorCapture → routers
- `error_capture.py` — Catches unhandled exceptions, writes to `error_logs` table, returns JSONResponse(500) instead of re-raising (fixes CORS on error responses)
- `pool.py` — psycopg ConnectionPool (min=2, max=30, 1h lifetime)
- `db.py` — `get_connection()` sets `statement_timeout=30s` and `lock_timeout=5s` per connection
- `core/config.py` — Settings from `.env`; `load_env_file()` uses CWD-relative path
- `core/security.py` — HMAC-SHA256 token auth (12h TTL), PBKDF2-SHA256 password hashing. JWT_SECRET fallback is `"dev-only-change-me"` — fine for local dev, must override in production.
- `api/` — 12 routers: auth, clipboard, exclusions, exports, health, holiday_lexicon, holiday_tags, keyword_compare, meta, product_selection, users
- `services/keyword_compare.py` — CTE-based compare engine. Public functions: `list_keyword_comparisons()`, `count_keyword_comparisons()`, `export_comparisons()`, `resolve_keyword_compare_range()`. Internal: `_ensure_range_cache()` with advisory lock, `_attach_holiday_tags()`.
- `services/keyword_compare_snapshot.py` — Multi-step snapshot refresh. Fixed dict_row/tuple_row compatibility (uses `isinstance(span, dict)` check).
- `services/holiday_tags.py` — Tag computation with word-boundary matching. Skips empty windows (no future-year false tags). `SET LOCAL statement_timeout = '300s'` for long batch.
- `services/scheduler.py` — Background cache refresh loop (NOT auto-started)

### Frontend (`frontend/src/`)

Now has proper component structure (was monolithic 2659-line App.tsx):

```
src/
├── App.tsx              (~900 lines, controller: state + handlers)
├── api.ts               API client functions
├── types.ts             TypeScript interfaces
├── utils.ts             Formatting helpers
├── styles.css           Apple-style design system
├── components/
│   ├── AppleSelect.tsx      Custom dropdown
│   ├── Sparkline.tsx        SVG trend chart
│   ├── Pagination.tsx       Reusable pagination
│   ├── LoginView.tsx        Login form
│   ├── Sidebar.tsx          Navigation sidebar
│   ├── DetailDrawer.tsx     Keyword detail slide-out
│   ├── OpportunitiesView.tsx  Scope bar + filter + table
│   ├── CompareView.tsx      17-column compare table
│   ├── ExportView.tsx       Export config
│   ├── ExclusionsView.tsx   Exclusion CRUD
│   ├── ClipboardView.tsx    Shared clipboard
│   ├── HolidayLexiconView.tsx  Holiday lexicon manager
│   ├── Field.tsx, Metric.tsx, Tag.tsx  Atom components
```

Side nav toggles 7 views: 机会池 → 我的收藏 → 横向对比 → 禁用词 → 数据导出 → 共享粘贴板 → 节日词库

**Compare table columns** (default visible unless noted):
关键词(always) → 类目 → 趋势图 → 末月搜索量 → 搜索量增量 → 增长率 → 环比(default hidden) → 同比(default hidden) → 排名变化 → 出现月数 → 平均搜索量(default hidden) → PPC → SPR → 类型 → 节日标签 → 状态 → 操作. Optional: 末月历史排名参考, 月度搜索量.

Column visibility persisted in localStorage (`compare_visible_columns_v3`).

### Admin System (`admin/`)

- `admin/app/main.py` — FastAPI app with SessionMiddleware, exception handler for AuthRequired → redirect to login
- `admin/app/core/auth.py` — `get_current_admin()` reads session, re-verifies user is active admin in DB
- `admin/app/routes/` — auth, dashboard, users (CRUD, Pydantic Literal validation), error_logs
- `admin/app/templates/` — 8 Jinja2 templates
- `admin/app/static/` — Apple-style CSS, minimal JS
- Uses JSON POST for user create/edit (not HTML form) to avoid UTF-8 double-encoding bug in Kludex's Starlette 1.3.1 + python-multipart 0.0.32

## Important Constraints

- **PYTHONPATH order matters**: `backend` must come before `admin` to avoid `app` package collision
- **`.env` duplication**: `--app-dir backend` changes CWD; copy `.env` to `backend/.env` if backend login fails
- `calculate_trends.py` requires `PYTHONPATH=backend`
- `keyword_compare_range_cache` is UNLOGGED — lost on PG restart
- Never let frontend connect directly to PostgreSQL
- Never rebuild caches on API startup
- SQL schema changes go in `sql/` directory files
- Do not mix backend/frontend frameworks
- Authoritative docs: `docs/` (9 files). Historical: `docs/archive/`.
- Windows admin required for: PostgreSQL service restart, firewall rules
- `admin/app/pool.py` has `close_pool()` registered as shutdown handler in `admin/app/main.py`

## Known Bugs Fixed (2026-07-01 to 2026-07-03)

- `keyword_compare_snapshot.py:77-79` — `span[0]` KeyError with dict_row; now uses `isinstance(span, dict)` check
- `error_capture.py:26` — Re-raising exception bypassed CORS; now returns JSONResponse(500)
- `security.py:48` — JWT_SECRET fallback noted; `.env` has JWT_SECRET set
- `002_metabase_views.sql:22-31` — Missing 6 trend_label_cn mappings added
- `check_app_users.py:11` — Hardcoded DATABASE_URL → `get_database_url()`
- `admin/auth.py` — Login failure now preserves account name in form
- `admin/users.py` — Pydantic models use Literal for role validation
- `admin/pool.py` — Shutdown handler registered
- CompareView thead/tbody column order mismatch fixed (trend_type before holiday)
- `holiday_tags.py` — Empty windows skipped (not tagged as suspected)
- `_attach_holiday_tags()` — Filters by compare range via `make_date()`
- `exports.py` — Uses `resolve_keyword_compare_range()` for consistent range filtering
- `HolidayLexiconView` — Per-item loading states, stale-cache warning on delete/toggle, success-only triggers

## Git

- **Remote:** `https://github.com/zouzou0905/database_thunder.git` (origin/main)
- **Local:** `main` tracking `origin/main`
- **User:** kai / 2132763052@qq.com
