# Keyword Trend Ops System

This project builds a keyword trend database and an operations workspace for Amazon ABA / SellerSprite CSV data.

Current business scope: filter meaningful keyword opportunities from large monthly keyword datasets. It does not currently depend on product pricing, profit, or full ASIN/competitor product dimensions.

中文文档入口：

- [文档入口](</F:/database/docs/README.md>)
- [系统总览](</F:/database/docs/01-系统总览.md>)
- [数据导入与刷新手册](</F:/database/docs/04-数据导入与刷新手册.md>)
- [启动部署与迁移](</F:/database/docs/05-启动部署与迁移.md>)

## Current Scope

Current scope focuses on the keyword operations workspace:

- PostgreSQL schema
- CSV inspection
- CSV import
- keyword normalization
- monthly metrics
- trend calculation
- keyword opportunity cache
- cross-month comparison snapshot
- FastAPI API
- React operations UI

## Project Layout

```text
docs/       Current authoritative docs; old notes are in docs/archive/
sql/        PostgreSQL schema, indexes, views
scripts/    Import, cleaning, trend calculation scripts
tests/      Parser tests
data/       Local data, reports, rejected rows, parquet archives
```

## Setup

Create `.env` from `.env.example` and update the database connection string:

```powershell
Copy-Item .env.example .env
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Initialize database:

```powershell
python scripts/init_db.py
```

## Inspect CSV Files

Run this before importing a month:

```powershell
python scripts/inspect_csv.py --input "C:\Users\admin\Desktop\aba数据\2026-03" --output data/reports/2026-03-inspect.json
```

## Import CSV Files

```powershell
python scripts/import_csv.py --month 2026-03 --marketplace UK --input "C:\Users\admin\Desktop\aba数据\2026-03"
```

The sample files use `£`, so `UK` may be the correct marketplace for those files. If the full dataset is not UK, pass the correct marketplace code.

## Calculate Trends

```powershell
python scripts/calculate_trends.py --analysis-month 2026-04 --marketplace UK
```

Trend labels become useful after at least two adjacent months are imported.

To recalculate all imported months in chronological order:

```powershell
python scripts/calculate_trends.py --all --marketplace UK
```

## Validate Code

```powershell
python -m unittest discover -s tests
python -m py_compile scripts\common.py scripts\init_db.py scripts\import_csv.py scripts\calculate_trends.py scripts\inspect_csv.py
```
