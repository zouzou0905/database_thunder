# Scripts

## 1. Initialize database

```powershell
python scripts/init_db.py
```

## 2. Inspect CSV files before import

```powershell
python scripts/inspect_csv.py --input "C:\Users\admin\Desktop\aba数据\2026-03" --output data/reports/2026-03-inspect.json
```

## 3. Import CSV files

```powershell
python scripts/import_csv.py --month 2026-03 --marketplace UK --input "C:\Users\admin\Desktop\aba数据\2026-03"
```

Use `--force` if a file was already recorded by hash and needs to be reprocessed.

## 4. Calculate trends and ops table

```powershell
python scripts/calculate_trends.py --analysis-month 2026-04 --marketplace UK
```

For a single month without previous-month data, most trend fields will be `new` or empty. Trend labels become useful after at least two adjacent months are imported.

Recalculate every imported month automatically:

```powershell
python scripts/calculate_trends.py --all --marketplace UK
```

Recalculate only one year:

```powershell
python scripts/calculate_trends.py --all --marketplace UK --year 2026
```

Recalculate a month range:

```powershell
python scripts/calculate_trends.py --all --marketplace UK --from-month 2025-04 --to-month 2026-04
```

## 5. Open Web workspace

The Web workspace uses a cache-first strategy:

```text
keyword_selection_candidates_monthly -> primary source
v_mb_product_selection_candidates -> fallback when a month/marketplace has no cache
```

The API returns `cached`. When `cached=false`, the frontend shows a slow-query warning because the backend is calculating from the live view.

Recommended monthly workflow:

```text
Import CSV -> calculate trends -> refresh keyword cache/snapshots -> open Web workspace
```

`scripts/calculate_trends.py` refreshes the product-selection cache and compare snapshot by default. Use `--skip-cache-refresh` only when you intentionally want to skip these write-heavy refresh steps.

To rebuild the cache for a specific month manually:

```powershell
python scripts\refresh_product_selection_cache.py --analysis-month 2026-04 --marketplace UK
```
